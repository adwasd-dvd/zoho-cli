# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest `cliq-193` unit hardening increment is complete**: `zoho cliq app-commands` now recognizes singleton camelCase aliases (`commandName` / `actionName`) in top-level and nested response payloads so maintenance responses without canonical wrappers no longer collapse to empty command output (focused tests: `tests/test_cli.py::test_cliq_app_commands_accepts_command_name_camel_case_alias_shape`, `tests/test_cli.py::test_cliq_app_commands_accepts_top_level_command_name_camel_case_alias_shape`, `tests/test_cli.py::test_cliq_app_commands_accepts_response_command_name_camel_case_alias_shape`).
3. **Next smallest step**: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence.

## Next
1. `cliq-193`: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence.
2. `cliq-193`: implement the next smallest output-hardening increment with focused unit coverage.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
