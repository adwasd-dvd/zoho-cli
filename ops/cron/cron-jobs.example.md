# Example cron job definitions

Use the matching prompt file from `ops/prompts/` for each recurring agent.

- planner → `ops/prompts/planner.md`
- builder → `ops/prompts/builder.md`
- verifier → `ops/prompts/verifier.md`
- fixer → `ops/prompts/fixer.md`
- release-manager → `ops/prompts/release-manager.md`
- nightly-smoke → `ops/prompts/nightly-smoke.md`

Suggested command context for each job:

1. open the repository root
2. read AGENTS.md and the corresponding prompt file
3. run only within the current branch or dedicated automation branch
4. update repo files instead of storing hidden local state
