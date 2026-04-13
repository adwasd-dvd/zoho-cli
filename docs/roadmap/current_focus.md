# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` got the next hardening slice**: `cliq apps` now unwraps `item` wrapper rows inside list payloads, with focused CLI regression coverage (`tests/test_cli.py::test_cliq_apps_accepts_data_list_wrapped_app_shape`, `tests/test_cli.py::test_cliq_apps_accepts_data_list_wrapped_item_shape`).
3. **Keep blocker-skipping active**: continue shipping/testable Cliq app-governance hardening slices and run one focused live verification pass per slice while app-account activation remains external.

## Next
1. `cliq-193`: run one focused live verification pass for the latest `cliq apps` item-wrapper hardening (`cliq status --check-auth` + `cliq apps --limit 10`) and archive evidence.
2. `cliq-193`: ship the next smallest app-governance output-hardening slice with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
