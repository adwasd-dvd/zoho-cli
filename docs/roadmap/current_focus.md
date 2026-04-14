# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest `cliq-193` hardening slice is complete**: `cliq app-get` now unwraps deeper `payload/response/result/data/records/record/item/...` wrapper stacks by extending app-row unwrapping depth (8 -> 16), with focused tests green (`tests/test_cli.py::test_cliq_app_get_accepts_top_level_payload_wrapper_shape`, `tests/test_cli.py::test_cliq_app_get_accepts_deep_data_records_record_item_wrapper_shape`).
3. **Next smallest step**: run one focused live rerun (`cliq status --check-auth` + `cliq app-get APP_PROBE_FAKE_<timestamp>`) and archive evidence for this hardening slice.

## Next
1. `cliq-193`: run one matching focused live rerun and archive evidence.
2. `cliq-193`: take the next smallest app-governance output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
