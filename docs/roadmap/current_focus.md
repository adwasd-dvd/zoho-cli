# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` focused live verification is refreshed**: latest `cliq app-get` wrapper-row hardening pass (`cliq status --check-auth` + `cliq app-get`) keeps auth/export readiness healthy and still classifies app-detail endpoints as `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_get_probe_summary_20260413_140324.json`).
3. **Keep blocker-skipping active**: continue moving on testable Cliq app-governance hardening slices while app-account activation remains external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-193`: take the next smallest app-governance output-hardening slice with focused unit coverage.
3. `cliq-193`: run one focused live verification pass for that new slice and archive evidence.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
