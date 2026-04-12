# Current Focus

## Immediate
1. **`cliq-190` is now closed with live evidence**: `cliq userfields` verification on happydistrouklimited succeeded (`count: 0`, auth healthy) and is archived at `tests/auto_pilot/reports/cliq190_probe_summary_20260412_192446.json`.
2. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` are blocked by API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
3. **Keep blocker-skipping loop active**: do not stall while waiting on admin-side activation.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-191`: if `cliq-165` remains externally blocked, start one smallest collaboration-productivity slice.
3. `crm-002`: remain blocked until CRM-enabled org access is available.
