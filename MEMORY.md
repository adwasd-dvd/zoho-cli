# MEMORY

Stable facts for this repo loop:
- Module order: Mail -> Cliq -> CRM
- Source of truth for tactical status: `ops/state/*.yml`
- Daily notes live in `../../memory/daily/`
- Anchors live in `../../memory/anchors/`
- Nightly verification should run `make release-gate` and `make ci` so packaging and formatting/lint drift are both visible.

Known recurring failure modes:
1. wrong workspace root (`workspace` vs `workspace-coder`)
2. absolute `/Volumes/...` paths accidentally treated as relative
3. brittle exact-match markdown edits
4. overlong prompt / run leading to timeout before real work starts

Test account status:
- `ai-dev@happy-distro.co.uk` token missing or invalid; refresh returns `invalid_code`
- Re-auth via OAuth flow required before live Cliq admin-plane verification (cliq-130)
