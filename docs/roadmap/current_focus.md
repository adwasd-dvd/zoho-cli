# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` payload-envelope hardening is delivered**: `cliq app-commands` and `cliq app-command-get` now unwrap top-level `payload` wrappers (plus deeper nested command rows) so payload-wrapped maintenance responses no longer degrade into blank command output; focused tests are green.
3. **Next smallest implementation step**: run one focused live rerun (`cliq status --check-auth` + `cliq app-command-get`) for this payload-envelope increment and archive evidence.

## Next
1. `cliq-193`: run one focused live rerun for the new payload-envelope increment and archive artifacts.
2. `cliq-193`: deliver the next small app-governance output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
