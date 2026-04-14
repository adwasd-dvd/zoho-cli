# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest cliq-193 unit hardening increment is complete**: `zoho cliq app-commands` + `zoho cliq app-command-get` now treat lowercase `helptext` as command-shaped row data during metadata-first row selection, so helptext-only command rows are no longer dropped behind metadata wrappers (focused tests: `test_cliq_app_commands_prefers_helptext_row_over_metadata_in_data_list`, `test_cliq_app_command_get_prefers_helptext_row_over_metadata_in_data_list`).
3. **Latest focused live rerun is current**: `cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_20260414_222805` keeps auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-command list endpoints remain `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260414_222805.json`).

## Next
1. `cliq-193`: implement the next smallest app-command output-hardening increment with focused tests.
2. `cliq-193`: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence for that increment.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
