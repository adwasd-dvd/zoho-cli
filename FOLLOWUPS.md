# FOLLOWUPS

- [x] Stabilize auto-pilot repo-root handling (`scenario_runner.py`, `run_cliq_live_probe.sh`, `run_cliq_alt_probe.sh`) so they run from either repo root or workspace root.
- [ ] Confirm the broader coder-agent startup path always lands on the canonical workspace.
- [ ] Replace any exact-text markdown update flow with section-based rewrite logic.
- [ ] Confirm mail path handling preserves absolute `/Volumes/...` inputs.
- [ ] Keep coding loop changes small enough to finish comfortably within the run timeout.
- [ ] Execute MR-first 7-10 workday plan: close remaining `cliq-193` slices, then land `platform-200/201/202`, then `crm-002` smoke closeout.
- [ ] Execute queued modularization slices (`platform-200/201/202`) as small no-behavior-change steps once the next `cliq-193` slice is merged.
- [ ] Post-release: evaluate official Zoho CRM server-side SDK and phase in safely via small slices (first candidate commands: `crm list` / `crm get`) after the current release ships.
- [x] Run one interactive `zoho login --with-cliq` re-auth that includes chat-read scope, then verify `zoho cliq chats --network happydistrouklimited` succeeds.
- [x] Re-run broad verification gate (`make release-gate && make ci`) after the latest cliq send fallback changes.
- [x] Re-run nightly broad verification gate while cliq-193 app-command hardening is active; latest run is green at 637 tests + wheel smoke + fmt/lint (`2026-04-16T14:29:00Z`).
- [x] Execute live native local-file upload probes (`cliq send` with voice/image/file local paths) and record endpoint matrix evidence to close cliq-155. (Latest evidence: `tests/auto_pilot/reports/cliq_local_media_matrix_live_20260411_185605.log` + `tests/auto_pilot/reports/cliq_retrieval_probe_20260411_185528.log`; still no attachment-positive success sample, currently classified as endpoint limitation.)
- [x] Re-run one cooldown-safe local upload probe against the new `/files` fallback path and confirm behavior on Cliq Chat File Sharing endpoints. (Latest evidence: `tests/auto_pilot/reports/cliq_local_media_matrix_cooldown_20260411_192105.json` shows local upload success on all 6 user/channel media probes; retrieval remains endpoint-limited per `tests/auto_pilot/reports/cliq_single_token_retrieval_after_upload_20260411_192343.json`.)
- [ ] Run one live `cliq export-chats` verification with maintenance export scopes (`ZohoCliq.OrganizationChats.READ` + `ZohoCliq.OrganizationMessages.READ`) (`list` + one `--chat-id` export) and archive sample output JSON for the new export tool. (Latest recheck after successful re-auth now fails with `inactive_appaccount_user`; evidence: `tests/auto_pilot/reports/cliq_export_chats_list_inactive_recheck_20260412_105646.json`, `tests/auto_pilot/reports/cliq_export_chat_inactive_recheck_20260412_105646.json`.)
- [ ] Run `./tests/auto_pilot/run_cliq_deep_scan.sh` with real test account/network inputs and archive one full evidence bundle (users + DM history + channel history + text/media send).
