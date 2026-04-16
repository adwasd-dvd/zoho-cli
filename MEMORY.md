# MEMORY

Stable facts for this repo loop:
- Module order: Mail -> Cliq -> CRM
- Source of truth for tactical status: `ops/state/*.yml`
- Daily notes live in `../../memory/daily/`
- Anchors live in `../../memory/anchors/`
- Nightly verification should run `make release-gate` and `make ci` so packaging and formatting/lint drift are both visible.
- Latest nightly broad verify (2026-04-16T14:29:00Z) is green: release-gate unit suite 637 passed + wheel smoke, and ci fmt/lint + pytest 637 passed.
- Modularization policy is now explicit in `docs/architecture/MODULARIZATION_RULES.md`; future extraction work should follow queued `platform-200/201/202` slices.

Known recurring failure modes:
1. wrong workspace root (`workspace` vs `workspace-coder`)
2. absolute `/Volumes/...` paths accidentally treated as relative
3. brittle exact-match markdown edits
4. overlong prompt / run leading to timeout before real work starts

Test account status:
- `ai-dev@happy-distro.co.uk` Cliq auth now includes chat-read scope and `zoho cliq chats --network happydistrouklimited` succeeds (`count: 0`), but native local multipart sends/retrieval probes are still needed to close cliq-155
- CRM live verification is still blocked because this account is not in a CRM org (`OAUTH_SCOPE_MISMATCH` on CRM APIs)
