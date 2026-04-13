# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` app-command-get sixth slice is now implemented**: command/client fallback routing and focused tests are green; next action is one focused live verification pass (`cliq status --check-auth` + `cliq app-command-get APP_PROBE_FAKE_<timestamp> CMD_PROBE_FAKE_<timestamp>`) to classify endpoint behavior.
3. **Keep blocker-skipping active**: continue moving on testable Cliq app-governance slices while app-account activation remains external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-193`: run one focused live verification pass for `cliq app-command-get` and archive evidence.
3. `cliq-193`: take the next smallest app-governance command/client slice with targeted tests.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
