# CODER START HERE (Zoho CLI)

- Work only inside `job/zoho-cli` (except `memory/` updates).
- Read in order: `MEMORY.md`, `FOLLOWUPS.md`, `WAITING_ON.md`, `docs/roadmap/current_focus.md`, `ops/state/*.yml`, latest `memory/daily/*`.
- Use `ops/state/*.yml` as source of truth.
- Smallest-step policy: Mail -> Cliq -> CRM, prefer blocker fixes over features.
- Run the smallest relevant test for each code change.
- If behavior changes, update `docs/releases/CHANGELOG.next.md`.
- Update relevant `ops/state/*.yml` and append `memory/daily/YYYY-MM-DD.md`.
- If tests pass for a real change, commit and push to `autobot/zoho-platform` (no force push, no merge to main).
