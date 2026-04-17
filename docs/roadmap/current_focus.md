# Current Focus

## Immediate
1. **Hybrid bridge v1.1 landed**: membrane path now includes preset resolution (`zoho-cliq` / `zoho-crm`) plus first explicit product wrapper (`zoho crm bridge-run --bridge membrane`) to reduce setup friction.
2. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
3. **`cliq-193` app-command live endpoint is external-deferred**: repeated focused reruns still fail app-command verification (`appCommandsError: empty_output`, CLI stderr `not_supported`) while scope readiness is healthy (`oauthReady: true`, `exportOauthReady: true`), so work stays capability-gated.
4. **Nightly broad verification remains green**: latest `make release-gate` and `make ci` broad run is green at 637 tests + wheel smoke + fmt/lint.
5. **Parallel track**: continue `platform-200/201/202` modularization while adding thin membrane-backed wrappers for high-value Cliq/CRM gaps.

## Next
1. `platform-203`: add first thin `cliq` membrane-backed wrapper command (explicit bridge flag) mirroring `crm bridge-run`.
2. `platform-200/201/202`: continue no-behavior-change modularization slices with parity checks.
3. `cliq-193`: keep unsupported endpoint work capability-gated and post-release deferred.
4. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
5. Define short migration matrix (which bridge wrappers should graduate to native next) for the next release cut.

## MR-first delivery estimate (blockers skipped)
- **Code-complete via mergeable slices**: **7-10 workdays**.
- **Full external-unblocked completion**: add **~1-3 weeks** depending on Zoho-side activation/support.

### Proposed 10-day execution window
1. **D1-D2**: `platform-200` guardrails MR (no behavior change).
2. **D3-D5**: `platform-201` command registration extraction in 1-2 MRs (no behavior change).
3. **D6-D8**: `platform-202` first cliq command-family extraction with parity tests.
4. **D9**: `crm-002` cooldown-safe live smoke (`fields/get/search`) + closeout updates.
5. **D10**: stabilization buffer (review comments, flaky reruns, release-note/state cleanup).

### Blocker handling policy for this window
- External/API/account blockers are marked **external-blocked** with report-path evidence.
- **3-strike unsupported rule**: when the same endpoint/check returns account/interface unsupported (`inactive_appaccount_user`, `not_supported`, or equivalent) 3 consecutive focused live runs, mark it **post-release deferred**, add capability-gated isolation, and continue unrelated slices.
- External blockers do **not** block merge of unrelated slices.
- Every MR must stay green on focused tests and formatting checks before merge.
