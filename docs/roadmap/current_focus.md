# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest cliq-193 focused live rerun is archived**: `cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_20260415_101821` kept auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-command list endpoints remained `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260415_101821.json`).
3. **Latest cliq-193 unit slice remains green**: `zoho cliq app-command-get` now preserves lowercase id aliases (`actionid`, `commandid`) in detail output (focused tests: `test_cliq_app_command_get_accepts_actionid_lowercase_alias_shape`, `test_cliq_app_command_get_accepts_commandid_lowercase_alias_shape`).

## Next
1. `cliq-193`: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence for the latest lowercase id-alias hardening.
2. `cliq-193`: take the next smallest app-command output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
