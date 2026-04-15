# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest cliq-193 unit hardening increment is complete**: `zoho cliq app-commands` + `zoho cliq app-command-get` now unwrap PascalCase wrapper keys (`Command`/`Action`, plus list wrappers `Commands`/`Actions`) so wrapped maintenance payloads preserve command id/name/description/status output (focused tests: `test_cliq_app_commands_accepts_pascal_case_command_wrapper_shape`, `test_cliq_app_command_get_accepts_pascal_case_action_wrapper_shape`).
3. **Latest focused live rerun is current**: `cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_20260415_002340` keeps auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-command list endpoints remain `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260415_002340.json`).

## Next
1. `cliq-193`: implement the next smallest app-command output-hardening increment with focused tests.
2. `cliq-193`: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
