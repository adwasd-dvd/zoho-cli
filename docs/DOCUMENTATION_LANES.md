# Documentation lanes and maintenance contract

This repository maintains three documentation lanes. Keep each lane accurate for its audience.

## Lane 1: coder development/operations docs

Audience: coding agents and maintainers working on active implementation.

Primary files:
- `AGENTS.md`
- `MEMORY.md`
- `FOLLOWUPS.md`
- `WAITING_ON.md`
- `ops/state/*.yml`
- `memory/daily/*.md`

Rules:
1. Update task/state files in the same working session as code/test changes.
2. Record blockers with concrete evidence.
3. Keep instructions executable, not aspirational.

## Lane 2: human user/project docs

Audience: human users and contributors.

Primary files:
- `README.md`
- `docs/architecture/*`
- `docs/roadmap/*`
- `docs/releases/CHANGELOG.next.md`

Rules:
1. Reflect what is actually shipped vs blocked.
2. Keep install/run steps copy-paste safe.
3. Update examples when command behavior changes.

## Lane 3: AI-user skill/docs/scripts

Audience: AI users (OpenClaw or similar) operating this CLI.

Primary files:
- `skill/SKILL.md`
- `integrations/openclaw/SKILL.md`
- `integrations/openclaw/SKILL_INDEX.md`
- `integrations/openclaw/bin/*`

Rules:
1. Keep skill instructions aligned with the current CLI surface.
2. Keep repository/package references accurate.
3. Keep update procedures deterministic and approval-gated for high-impact operations.

## Required sync workflow after any CLI change

When CLI behavior changes (new command, renamed flag, output/schema change, install flow change):

1. Update Lane 2 docs (`README`/`docs/*`) with user-facing impact.
2. Update Lane 3 skill/docs/scripts with AI-facing usage changes.
3. Add or adjust focused tests when docs describe new behavior.
4. Record status in Lane 1 state files (`ops/state/*`).

## AI-user update alignment protocol (GitHub pull)

Before an AI user updates local CLI/skill after pulling from GitHub:

1. Compare update range (`git log --oneline <old>..HEAD`).
2. Compare user-impact docs (`README.md`, `docs/releases/CHANGELOG.next.md`).
3. Compare AI-impact docs (`skill/SKILL.md`, `integrations/openclaw/*`).
4. Summarize deltas:
   - changed CLI commands/flags/output
   - changed skill files/usages
   - changed install/update scripts
5. Confirm understanding, then update local CLI and local skill together.
6. Run minimum smoke checks to verify alignment.

Do not update only one side (CLI or skill) when the other changed.
