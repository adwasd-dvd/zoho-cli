# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest `cliq-193` unit slice is green**: app-command list/detail normalization now accepts flat-lower command-name/display aliases (`commandname` / `actionname` / `displayname`), so alias-only maintenance payloads preserve command names; focused regressions passed (`4 passed`, targeted `tests/test_cli.py` selectors).
3. **Latest `cliq-193` focused live rerun remains blocked externally**: `cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_20260415_143304` kept auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-command list endpoints remained `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260415_143304.json`).
4. **Nightly broad verification is green**: `make release-gate` and `make ci` both passed (`575` tests, wheel smoke, fmt/lint all green).

## Next
1. `cliq-193`: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence for the latest alias hardening slice.
2. `cliq-193`: take the next smallest app-command output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
