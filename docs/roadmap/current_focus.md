# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest focused unit hardening is complete**: `cliq app-commands` + `cliq app-command-get` now treat Pascal/camel action-id aliases (`ActionId` / `ActionID` / `actionID`) as command-shaped rows in metadata-first wrapper lists, with focused tests green (`tests/test_cli.py::test_cliq_app_commands_prefers_pascal_action_id_row_over_metadata_in_data_list`, `tests/test_cli.py::test_cliq_app_command_get_prefers_pascal_action_id_row_over_metadata_in_data_list`).
3. **Next smallest step**: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence, then take the next cliq-193 output-hardening increment.

## Next
1. `cliq-193`: implement the next smallest output-hardening increment with focused CLI unit tests.
2. `cliq-193`: run one matching focused live rerun and archive evidence for that increment.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
