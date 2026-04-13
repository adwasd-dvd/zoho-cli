# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` focused live verification refreshed**: latest detail `record`-wrapper hardening is now live-verified (`cliq status --check-auth` + `cliq app-command-get`) with healthy auth/export readiness and endpoint classification still `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_command_get_probe_summary_20260413_170344.json`).
3. **Keep blocker-skipping active**: continue shipping/testable Cliq app-governance hardening slices and run one focused live verification pass per slice while app-account activation remains external.

## Next
1. `cliq-193`: ship the next smallest app-governance output-hardening slice with focused tests.
2. `cliq-193`: run one focused live verification pass for that new slice and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
