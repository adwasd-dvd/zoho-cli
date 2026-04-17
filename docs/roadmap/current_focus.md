# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` live endpoint remains externally blocked**: the latest focused rerun (`20260417_033228`) still fails app-command verification (`appCommandsError: empty_output` in `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260417_033228.json`, CLI stderr `not_supported`), and the same probe shows test-config Cliq scopes are currently missing (`oauthReady: false`, `exportOauthReady: false` in `tests/auto_pilot/reports/cliq193_status_20260417_033228.json`).
3. **Latest `cliq-193` unit hardening slice is complete**: app-command list/detail normalization now also accepts mixed snake+Pascal-tail status aliases (`command_Status` / `action_Status`, plus `Command_Status` / `Action_Status`) in command-row hint detection and output status mapping, with focused tests passing (`2 passed`).
4. **Nightly broad verification remains green**: latest `make release-gate` and `make ci` broad run is green at 637 tests + wheel smoke + fmt/lint.
5. **Small-step modularization workflow is now explicitly queued**: added `platform-200/201/202` to `ops/state/work_queue.yml` and documented guardrails in `docs/architecture/MODULARIZATION_RULES.md`.

## Next
1. `cliq-193`: first run one Cliq re-auth (`zoho login --with-cliq --with-cliq-export`) for the test config, then rerun the focused live probe (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`), then continue the next smallest app-command output-hardening unit slice with focused tests.
2. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
3. `crm-002`: auth/API blocker is cleared (`oauthReady: true`; live `crm modules` + `crm list --module Leads --limit 1` succeed). Finish cooldown-safe `fields` + `get` + `search` smoke and close the task.
4. `platform-200`: after the next cliq-193 slice lands, start the modularization guardrail rollout (rules enforced first, then registry/commands extraction as no-behavior-change slices).
