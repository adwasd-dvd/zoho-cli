# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` are blocked by API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-191` focused live verification is archived**: `zoho cliq meetings --limit 10` now classifies calls/meetings endpoints as `not_supported` on current token/network even after `/calls` + `/admin/calls` fallback hardening (`tests/auto_pilot/reports/cliq191_probe_summary_20260412_210519.json`).
3. **Keep blocker-skipping loop active**: do not stall while waiting on admin-side activation.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-192`: start the first smallest platform-extension command/client slice with targeted tests while `cliq-165` remains externally blocked.
3. `crm-002`: remain blocked until CRM-enabled org access is available.
