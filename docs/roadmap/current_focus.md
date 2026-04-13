# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Focused `cliq-193` live verification rerun is complete**: `cliq status --check-auth` + `cliq app-command-get` (probe ids `APP_PROBE_FAKE_20260413_210341` / `CMD_PROBE_FAKE_20260413_210341`) keeps auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-command detail endpoints remain `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_command_get_probe_summary_20260413_210341.json`).
3. **Next step is the next smallest `cliq-193` output-hardening increment** with focused unit coverage.

## Next
1. `cliq-193`: ship the next smallest app-governance output-hardening increment with focused unit coverage.
2. `cliq-193`: run one focused live pass (`cliq status --check-auth` + one app-governance command) and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
