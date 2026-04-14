# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest cliq-193 unit hardening increment is complete**: `zoho cliq app-commands` + `zoho cliq app-command-get` now normalize lowercase `helptext` description aliases (alongside existing `help` / `Help` / `HelpText` keys), with focused tests green (`test_cliq_app_commands_accepts_helptext_alias_shape`, `test_cliq_app_command_get_accepts_helptext_alias_shape`).
3. **Latest focused live rerun is archived**: `cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_20260414_210237` keeps auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-command list endpoints remain `not_supported`.

## Next
1. `cliq-193`: implement the next smallest output-hardening increment with focused tests.
2. `cliq-193`: run one matching focused live rerun (`cliq status --check-auth` + one app-governance command) and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
