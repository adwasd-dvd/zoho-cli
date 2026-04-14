# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` app payload-envelope hardening is in**: `zoho cliq apps` and `zoho cliq app-get` now unwrap top-level `payload` envelopes, and app-detail row unwrapping depth was raised so payload-wrapped responses no longer fall back to id-only output (focused tests: `tests/test_cli.py::test_cliq_apps_accepts_top_level_response_wrapper_shape`, `tests/test_cli.py::test_cliq_apps_accepts_top_level_payload_wrapper_shape`, `tests/test_cli.py::test_cliq_app_get_accepts_top_level_response_wrapper_shape`, `tests/test_cli.py::test_cliq_app_get_accepts_top_level_payload_wrapper_shape`).
3. **Next smallest step**: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-get APP_PROBE_FAKE_<timestamp>`) and archive evidence.

## Next
1. `cliq-193`: run one focused live rerun for the latest app payload-envelope hardening and archive evidence.
2. `cliq-193`: take the next small app-governance output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
