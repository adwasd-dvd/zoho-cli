# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest `cliq-193` focused live rerun remains externally blocked**: `cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_20260415_192925` kept auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-command list endpoints remained `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260415_192925.json`).
3. **Latest `cliq-193` unit slice is green**: app-command list/detail normalization now accepts snake+camel and uppercase-snake display-name aliases (`command_displayName` / `action_displayName`, `COMMAND_DISPLAYNAME` / `ACTION_DISPLAYNAME`), with focused regressions passing.
4. **Nightly broad verification remains green**: `make release-gate` and `make ci` are still green from the latest broad run (`575` tests, wheel smoke, fmt/lint all green).

## Next
1. `cliq-193`: take the next smallest app-command output-hardening increment with focused tests.
2. `cliq-193`: after the next unit increment, run one matching focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
