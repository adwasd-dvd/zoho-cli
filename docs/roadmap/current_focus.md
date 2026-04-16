# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` live endpoint remains externally blocked**: focused reruns still show healthy auth/export readiness (`oauthReady: true`, `exportOauthReady: true`) while app-command endpoints stay unavailable (`not_supported` in `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260416_025449.json`).
3. **Probe-summary automation gap is now fixed**: added `tests/auto_pilot/cliq193_probe_summary.py` + focused tests (`tests/test_cliq193_probe_summary.py`), and backfilled missing summary evidence for `20260416_025358`.
4. **Nightly broad verification remains green**: latest `make release-gate` and `make ci` broad run is still green.

## Next
1. `cliq-193`: run one fresh focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and capture a non-empty app-command output artifact.
2. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
3. `crm-002`: remain blocked until CRM-enabled org access is available.
