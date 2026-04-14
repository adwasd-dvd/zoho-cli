# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest focused unit hardening is complete**: `cliq-193` now makes `cliq app-command-get` prefer command-shaped rows over metadata rows in metadata-first wrapper lists (for example `payload.data: [{meta: ...}, {command: {...}}]`), preventing blank fallback command names; focused tests are green (`tests/test_cli.py::test_cliq_app_command_get_prefers_command_row_over_metadata_in_data_list`, `tests/test_cli.py::test_cliq_app_command_get_accepts_top_level_payload_wrapper_shape`).
3. **Next smallest step**: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-command-get APP_PROBE_FAKE_<stamp> CMD_PROBE_FAKE_<stamp>`) and archive evidence.

## Next
1. `cliq-193`: run one matching focused live rerun for the metadata-first list hardening and archive evidence.
2. `cliq-193`: implement the next smallest output-hardening increment with focused CLI unit coverage.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
