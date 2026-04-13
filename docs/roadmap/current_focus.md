# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` remains active with fresh live verification**: focused live `cliq status --check-auth` + `cliq apps --limit 10` keeps auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-list endpoints still classify as `not_supported` (`tests/auto_pilot/reports/cliq193_apps_probe_summary_20260413_132254.json`).
3. **Keep blocker-skipping active**: continue moving on testable Cliq app-governance hardening slices while app-account activation remains external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-193`: take the next smallest app-governance output-hardening slice with focused unit coverage.
3. `cliq-193`: run one focused live verification pass for that slice and archive evidence.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
