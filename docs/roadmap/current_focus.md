# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest focused unit increment is complete**: `cliq-193` now unwraps deeper app-command detail wrappers (`data.records.record[].item`, depth `10 -> 16`) with focused regressions green (`tests/test_cli.py::test_cliq_app_command_get_accepts_deep_data_records_record_item_wrapper_shape`, `tests/test_cli.py::test_cliq_app_command_get_accepts_extra_deep_record_item_wrapper_shape`).
3. **Next smallest step**: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-command-get APP_PROBE_FAKE_<stamp> CMD_PROBE_FAKE_<stamp>`) and archive evidence.

## Next
1. `cliq-193`: run the matching focused live rerun for the latest app-command detail hardening and archive evidence.
2. `cliq-193`: take the next smallest output-hardening increment with focused unit coverage.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
