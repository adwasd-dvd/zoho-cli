# Cron plan for OpenClaw or other unattended runners

## Recommended job split

1. planner — twice daily
2. builder — every 30 minutes
3. verifier — every 45 minutes
4. fixer — every hour
5. release-manager — daily
6. nightly-smoke — daily overnight

## Suggested schedule

| Job | Cron | Purpose |
|---|---|---|
| planner | `0 8,20 * * *` | pick the next smallest useful task |
| builder | `*/30 * * * *` | write code for the active task |
| verifier | `15,59 * * * *` | run tests and record failures |
| fixer | `10 * * * *` | fix the current blocker |
| release-manager | `30 18 * * *` | release only when gates are green |
| nightly-smoke | `0 2 * * *` | broad regression sweep |

## Operating rule

All jobs must read and write the shared files in `ops/state/`.
That state is the source of truth. Do not use memory-only progress.
