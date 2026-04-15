# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest cliq-193 focused live rerun is archived**: `cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_20260415_132834` kept auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-command list endpoints remained `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260415_132834.json`).
3. **Latest cliq-193 unit slice remains green**: app-command list/detail normalization now also accepts uppercase command-prefixed help aliases (`COMMANDHELP`/`ACTIONHELP`, plus `COMMAND_HELP`/`ACTION_HELP`) and remains green (focused tests: `test_cliq_app_commands_accepts_uppercase_command_prefixed_help_alias_shape`, `test_cliq_app_command_get_accepts_uppercase_command_prefixed_help_alias_shape`, plus uppercase alias regressions).

## Next
1. `cliq-193`: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence for the latest uppercase command-prefixed help-alias hardening.
2. `cliq-193`: take the next smallest app-command output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
