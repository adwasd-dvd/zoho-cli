# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest cliq-193 hardening slice is complete**: `zoho cliq app-command-get` metadata-first row selection now treats wrapped action-id rows inside wrapper entries (for example `{payload: {action_id: ...}}`) as command-shaped rows, so wrapped metadata rows no longer mask valid wrapped command rows in `payload.data`.
3. **Focused live evidence remains fresh**: `cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_20260415_081108` keeps auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-command list endpoints remain `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260415_081108.json`).

## Next
1. `cliq-193`: take the next smallest app-command output-hardening increment with focused tests.
2. `cliq-193`: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence for that hardening slice.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
