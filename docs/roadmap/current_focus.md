# Current Focus

## Immediate
1. **`cliq-171` scheduled lifecycle**: `schedule`/`scheduled`/`scheduled-get`/`scheduled-cancel` are now implemented with capability-gated fallbacks; run one live verification bundle and archive evidence.
2. **Keep blocker-skipping loop active**: do not stall on `cliq-165` export-scope re-auth or thread endpoint limitations; continue with queued Cliq work when human interaction is required.
3. **Thread-plane status**: live probe evidence is archived and currently classified as endpoint limitation on happydistrouklimited (`tests/auto_pilot/reports/cliq_thread_probe_summary_20260412_044149.json`).

## Next
1. `cliq-171`: scheduled message lifecycle (schedule/list/get/cancel)
2. `cliq-172`: search + attachment retrieval parity closeout
3. `cliq-180` / `cliq-181`: bot operations + chat control plane expansion
