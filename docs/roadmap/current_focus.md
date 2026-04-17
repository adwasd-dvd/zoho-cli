# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` live endpoint remains externally blocked**: the latest focused rerun (`20260417_005822`) still shows healthy auth/export readiness (`oauthReady: true`, `exportOauthReady: true`) while app-command verification fails (`appCommandsError: empty_output` in `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260417_005822.json`, with CLI returning `not_supported` to stderr).
3. **Latest `cliq-193` unit hardening slice is complete**: app-command list/detail normalization now also accepts mixed snake+Pascal-tail mode status aliases (`command_Mode` / `action_Mode`, plus `Command_Mode` / `Action_Mode`) in command-row hint detection and output status mapping, with focused tests passing (`2 passed`).
4. **Nightly broad verification remains green**: latest `make release-gate` and `make ci` broad run is green at 637 tests + wheel smoke + fmt/lint.
5. **Small-step modularization workflow is now explicitly queued**: added `platform-200/201/202` to `ops/state/work_queue.yml` and documented guardrails in `docs/architecture/MODULARIZATION_RULES.md`.

## Next
1. `cliq-193`: take the next smallest app-command output-hardening unit slice with focused tests, then run one fresh focused live probe (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) to refresh blocker evidence.
2. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
3. `crm-002`: remain blocked until CRM-enabled org access is available.
4. `platform-200`: after the next cliq-193 slice lands, start the modularization guardrail rollout (rules enforced first, then registry/commands extraction as no-behavior-change slices).
