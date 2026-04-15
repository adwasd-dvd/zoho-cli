# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest cliq-193 blocker fix is complete**: `zoho cliq app-commands` metadata-first filtering now skips metadata-only `meta` rows when stronger command rows coexist, resolving the two failing regressions (`test_cliq_app_commands_prefers_command_rows_over_metadata_in_data_list`, `test_cliq_app_commands_prefers_pascal_action_id_row_over_metadata_in_data_list`) in focused reruns.
3. **Focused live evidence is freshly refreshed**: `cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_20260415_020441` keeps auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-command list endpoints remain `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260415_020441.json`).

## Next
1. `cliq-193`: take the next smallest app-command output-hardening increment with focused tests.
2. `cliq-193`: after that unit hardening, run one matching focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
