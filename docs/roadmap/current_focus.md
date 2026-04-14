# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest focused unit increment is complete**: `zoho cliq app-commands` + `zoho cliq app-command-get` now accept display-name aliases (`displayName` / `display_name`) when canonical command name fields are absent; focused tests are green (`tests/test_cli.py::test_cliq_app_commands_accepts_display_name_camel_case_alias_shape`, `tests/test_cli.py::test_cliq_app_command_get_accepts_payload_data_display_name_camel_case_alias_shape`).
3. **Next smallest step**: run one matching focused live rerun (`zoho cliq status --check-auth` + `zoho cliq app-command-get APP_PROBE_FAKE_<stamp> CMD_PROBE_FAKE_<stamp>`) and archive evidence, then continue with the next `cliq-193` output-hardening increment.

## Next
1. `cliq-193`: run one matching focused live rerun for the new display-name alias hardening (`cliq status --check-auth` + `cliq app-command-get ...`) and archive evidence.
2. `cliq-193`: implement the next smallest output-hardening increment with focused unit coverage.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
