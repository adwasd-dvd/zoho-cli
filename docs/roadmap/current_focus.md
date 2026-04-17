# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` live endpoint remains externally blocked**: the latest focused rerun (`20260417_071921`) still fails app-command verification (`appCommandsError: empty_output` in `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260417_071921.json`, CLI stderr `not_supported`), while companion status shows test-config Cliq scopes are healthy (`oauthReady: true`, `exportOauthReady: true` in `tests/auto_pilot/reports/cliq193_status_20260417_071921.json`).
3. **Latest `cliq-193` unit hardening slice is complete**: app-command list/detail normalization now also accepts mixed snake+uppercase-tail status aliases (`command_STATUS` / `action_STATUS`, plus Pascal-prefix companions) in command-row hint detection and output status mapping, with focused tests passing (`2 passed`).
4. **Nightly broad verification remains green**: latest `make release-gate` and `make ci` broad run is green at 637 tests + wheel smoke + fmt/lint.
5. **Small-step modularization workflow is now explicitly queued**: added `platform-200/201/202` to `ops/state/work_queue.yml` and documented guardrails in `docs/architecture/MODULARIZATION_RULES.md`.

## Next
1. `cliq-193`: continue the next smallest app-command output-hardening unit slice with focused tests, then rerun the focused live probe (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) to refresh blocker evidence.
2. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
3. `crm-002`: completed live CRM smoke (`fields` + `list` + `get` + `search`) on the test account; keep monitoring only.
4. `platform-200`: after the next cliq-193 slice lands, start the modularization guardrail rollout (rules enforced first, then registry/commands extraction as no-behavior-change slices).
5. `crm-003` (post-release): add Zoho CRM official server-side SDK evaluation + phased adoption plan to the first maintenance follow-up train.

## MR-first delivery estimate (blockers skipped)
- **Code-complete via mergeable slices**: **7-10 workdays**.
- **Full external-unblocked completion**: add **~1-3 weeks** depending on Zoho-side activation/support.

### Proposed 10-day execution window
1. **D1-D3**: finish remaining `cliq-193` hardening slices, each as standalone MR with focused tests + one live probe evidence refresh.
2. **D4**: `platform-200` guardrails MR (no behavior change).
3. **D5-D6**: `platform-201` command registration extraction in 1-2 MRs (no behavior change).
4. **D7-D8**: `platform-202` first cliq command-family extraction with parity tests.
5. **D9**: `crm-002` cooldown-safe live smoke (`fields/get/search`) + closeout updates.
6. **D10**: stabilization buffer (review comments, flaky reruns, release-note/state cleanup).

### Blocker handling policy for this window
- External/API/account blockers are marked **external-blocked** with report-path evidence.
- External blockers do **not** block merge of unrelated slices.
- Every MR must stay green on focused tests and formatting checks before merge.
