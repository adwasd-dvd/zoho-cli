# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest cliq-193 hardening slice is complete**: `zoho cliq app-commands` + `zoho cliq app-command-get` now normalize command-prefixed help aliases (`commandHelp`/`command_help`, `commandHelpText`/`command_help_text`, plus action-prefixed companions), preserving command descriptions when maintenance payloads omit canonical description/help keys.
3. **Focused live evidence is freshly refreshed**: `cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_20260415_020441` keeps auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-command list endpoints remain `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260415_020441.json`).

## Next
1. `cliq-193`: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence after the latest help-alias hardening.
2. `cliq-193`: after that live rerun, take the next smallest app-command output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
