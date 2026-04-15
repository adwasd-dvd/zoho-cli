# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest cliq-193 hardening slice is complete**: `zoho cliq app-commands` metadata-first wrapper traversal now prefers wrapped entries carrying command hints, so rows like `{payload: {action_id: ...}}` are selected ahead of wrapped metadata rows in mixed `payload.data` lists.
3. **Focused unit evidence is green**: `tests/test_cli.py::test_cliq_app_commands_prefers_wrapped_action_row_over_wrapped_metadata_in_payload_data_list` plus companion metadata-wrapper regressions all pass.

## Next
1. `cliq-193`: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence for this hardening slice.
2. `cliq-193`: take the next smallest app-command output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
