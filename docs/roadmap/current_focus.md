# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` output-shape hardening remains active while app-account activation is blocked**: app-governance list/detail commands now handle singleton wrappers across top-level payloads plus nested/detail wrappers, and list commands now also unwrap list-row singular wrappers (`app`/`permission`/`install`/`command`) so wrapped maintenance list rows no longer degrade into empty/partial output.
3. **Keep blocker-skipping active**: continue moving on testable Cliq app-governance slices while app-account activation remains external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-193`: run one focused live verification pass for the new list-row wrapper hardening (`cliq status --check-auth` + one app-governance list command) and archive evidence.
3. `cliq-193`: take the next smallest app-governance command/client/output-hardening slice if the live pass remains endpoint-limited.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
