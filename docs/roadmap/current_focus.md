# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest `cliq-193` output-hardening increment is complete**: `zoho cliq apps` now unwraps deeper `payload/response/result/data/records/record/item` wrapper chains by extending app-row unwrapping depth (3 -> 16); focused tests are green (`tests/test_cli.py::test_cliq_apps_accepts_top_level_payload_wrapper_shape`, `tests/test_cli.py::test_cliq_apps_accepts_deep_data_records_record_item_wrapper_shape`).
3. **Next smallest step**: run one matching focused live rerun (`cliq status --check-auth` + `cliq apps --limit 10`) and archive evidence.

## Next
1. `cliq-193`: run one focused live `cliq apps` rerun for the new deep-wrapper hardening and archive evidence.
2. `cliq-193`: take the next smallest output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
