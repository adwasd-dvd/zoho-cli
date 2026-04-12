# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` are blocked by API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-191` is now on the fourth smallest slice**: `zoho cliq meetings` now also probes `/calls` + `/admin/calls` fallback candidates before classifying calls/meetings endpoints.
3. **Keep blocker-skipping loop active**: do not stall while waiting on admin-side activation.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-191`: run one focused live verification pass for `zoho cliq meetings` and archive evidence for endpoint behavior on current token/network.
3. `crm-002`: remain blocked until CRM-enabled org access is available.
