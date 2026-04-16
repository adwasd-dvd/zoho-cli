# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` live endpoint remains externally blocked**: the latest focused rerun (`20260416_104530`) still shows healthy auth/export readiness (`oauthReady: true`, `exportOauthReady: true`) while app-command verification fails (`appCommandsError: empty_output` in `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260416_104530.json`, with CLI returning `not_supported` to stderr).
3. **Latest `cliq-193` unit hardening slice is complete**: app-command list/detail normalization now also accepts Pascal-kebab displayname aliases (`Command-DisplayName`/`Action-DisplayName`) plus kebab help aliases (`command-help`/`action-help`, `command-help-text`/`action-help-text`), with focused tests passing (`4 passed`).
4. **Probe-summary automation gap is fixed**: `tests/auto_pilot/cliq193_probe_summary.py` is in place with focused tests (`tests/test_cliq193_probe_summary.py`), and the missing `20260416_025358` summary was backfilled.
5. **Nightly broad verification remains green**: latest `make release-gate` and `make ci` broad run is still green.

## Next
1. `cliq-193`: take the next smallest app-command output-hardening unit slice with focused tests, then run one fresh focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) to keep blocker evidence current.
2. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
3. `crm-002`: remain blocked until CRM-enabled org access is available.
