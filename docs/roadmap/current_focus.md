# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` response-envelope output hardening is complete**: `cliq apps` + `cliq app-get` now unwrap top-level `response`/`result` wrappers (including nested `data.records.record.item`) with focused unit coverage (`tests/test_cli.py::test_cliq_apps_accepts_top_level_response_wrapper_shape`, `tests/test_cli.py::test_cliq_app_get_accepts_top_level_response_wrapper_shape`).
3. **Focused live rerun is now archived**: `cliq status --check-auth` + `cliq app-get APP_PROBE_FAKE_20260413_214829` keeps auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-detail endpoints remain `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_get_probe_summary_20260413_214829.json`).

## Next
1. `cliq-193`: ship the next smallest app-governance output-hardening increment with focused unit coverage.
2. `cliq-193`: run one focused live pass for that increment and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
