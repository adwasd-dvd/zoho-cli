You are taking over the `zoho-cli` repository as a long-lived development agent.

Read in this order:
1. AGENTS.md
2. docs/architecture/MULTI_PRODUCT_PLAN.md
3. docs/roadmap/current_focus.md
4. ops/state/module_status.yml
5. ops/state/work_queue.yml
6. ops/state/active_task.yml
7. ops/state/test_status.yml
8. ops/state/release_status.yml
9. ops/state/bug_backlog.yml
10. docs/releases/CHANGELOG.next.md

Your operating order is:
- first stabilize Zoho Mail
- then add Zoho Cliq
- then add Zoho CRM

Today, do this:
- inspect the current active task
- make the smallest useful code change toward that task
- add or update narrow tests
- run the smallest relevant test slice
- update state files and changelog draft
- produce a concise summary of what changed, what failed, and what should happen next

Do not skip the state files. Do not jump ahead to Cliq or CRM before Mail is stable.
