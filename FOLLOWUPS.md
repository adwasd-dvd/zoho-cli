# FOLLOWUPS

- [x] Stabilize auto-pilot repo-root handling (`scenario_runner.py`, `run_cliq_live_probe.sh`, `run_cliq_alt_probe.sh`) so they run from either repo root or workspace root.
- [ ] Confirm the broader coder-agent startup path always lands on the canonical workspace.
- [ ] Replace any exact-text markdown update flow with section-based rewrite logic.
- [ ] Confirm mail path handling preserves absolute `/Volumes/...` inputs.
- [ ] Keep coding loop changes small enough to finish comfortably within the run timeout.
- [x] Run one interactive `zoho login --with-cliq` re-auth that includes chat-read scope, then verify `zoho cliq chats --network happydistrouklimited` succeeds.
- [x] Re-run broad verification gate (`make release-gate && make ci`) after the latest cliq send fallback changes.
- [x] Execute live native local-file upload probes (`cliq send` with voice/image/file local paths) and record endpoint matrix evidence to close cliq-155. (Latest evidence: `tests/auto_pilot/reports/cliq_local_media_matrix_live_20260411_185605.log` + `tests/auto_pilot/reports/cliq_retrieval_probe_20260411_185528.log`; still no attachment-positive success sample, currently classified as endpoint limitation.)
- [x] Re-run one cooldown-safe local upload probe against the new `/files` fallback path and confirm behavior on Cliq Chat File Sharing endpoints. (Latest evidence: `tests/auto_pilot/reports/cliq_local_media_matrix_cooldown_20260411_192105.json` shows local upload success on all 6 user/channel media probes; retrieval remains endpoint-limited per `tests/auto_pilot/reports/cliq_single_token_retrieval_after_upload_20260411_192343.json`.)
- [ ] Run one live `cliq export-chats` verification with maintenance export scopes (`ZohoCliq.OrganizationChats.READ` + `ZohoCliq.OrganizationMessages.READ`) (`list` + one `--chat-id` export) and archive sample output JSON for the new export tool.
- [ ] Run `./tests/auto_pilot/run_cliq_deep_scan.sh` with real test account/network inputs and archive one full evidence bundle (users + DM history + channel history + text/media send).
