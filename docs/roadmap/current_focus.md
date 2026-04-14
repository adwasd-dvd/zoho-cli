# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest `cliq-193` unit hardening increment is complete**: `zoho cliq app-command-get` now unwraps deeper `data.records.record[].item` wrapper stacks (command-row depth `8 -> 10`), so deep maintenance wrapper rows no longer degrade `name` to wrapper-shaped output (`tests/test_cli.py::test_cliq_app_command_get_accepts_deep_data_records_record_item_wrapper_shape`).
3. **Next smallest step**: run one focused live rerun for this latest `cliq-193` hardening (`cliq status --check-auth` + `cliq app-command-get`) and archive evidence.

## Next
1. `cliq-193`: run one matching focused live rerun for the latest deep `app-command-get` wrapper hardening and archive evidence.
2. `cliq-193`: take the next smallest app-governance output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
