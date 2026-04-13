# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` focused live rerun is refreshed**: `cliq status --check-auth` + `cliq app-command-get` evidence is now archived at `tests/auto_pilot/reports/cliq193_app_command_get_probe_summary_20260413_234955.json`; auth/export readiness is still healthy and app-command detail endpoints remain `not_supported`.
3. **Next smallest implementation step**: ship the next cliq-193 app-governance output-hardening increment with focused unit tests.

## Next
1. `cliq-193`: deliver one small app-governance output-hardening increment with focused tests.
2. `cliq-193`: run one focused live rerun for that increment and archive artifacts.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
