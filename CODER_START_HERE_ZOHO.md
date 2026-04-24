# CODER START HERE — ZOHO

Work from `job/zoho-cli` as the project root.

Execution order:
1. `MEMORY.md`
2. `FOLLOWUPS.md`
3. `WAITING_ON.md`
4. `docs/roadmap/current_focus.md`
5. `ops/state/*.yml`
6. newest `../../memory/daily/*.md`

Mission:
Advance the project by the **smallest real step** following the module order:
**Mail -> Cliq -> CRM**.

Rules:
- Fix blockers before features.
- Prefer one coherent change over many scattered edits.
- Run the smallest relevant test.
- Update state files and daily memory every time.
- Update `docs/releases/CHANGELOG.next.md` when behavior changes.
- Commit and push only when the change is real and verified.
- 3-strike external blocker policy: if the same live check returns account/interface unsupported signals (`inactive_appaccount_user`, `not_supported`, or equivalent) 3 times in a row, mark that feature as post-release deferred, isolate it behind capability-gated behavior, and continue with unrelated roadmap slices.

Path rules:
- `/Volumes/...` is absolute. Never prefix it with the workspace path.
- If a file path resolves under both `workspace` and `workspace-coder`, treat the existing file as canonical and stop duplicating roots.

Status-file rule:
- Do not use fragile exact-text replacement for markdown progress files.
- Rewrite by heading block or regenerate the file completely.

If startup control files are missing, create the minimum viable version and continue.
